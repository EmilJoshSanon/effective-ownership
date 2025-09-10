# 1. Adjust upper limit for all companies where upper limit is not possible due to sum of lower limits other owners exceeding residual ownership.
# 2. Calculate effective ownership for all owners of companies in a circular ownership.
# 3. Calculate effective ownership for all owners in the ownship tree.
# 4. In cases where a company has two effective ownerships of the focus company, the two branches are summed together.

# %%
import json
import pydantic
import pandas as pd


class OwnershipNode(pydantic.BaseModel):
    id: str
    source: int
    source_name: str
    source_depth: int
    target: int
    target_name: str
    target_depth: int
    share: str
    init_lower_share: float | None = None
    init_upper_share: float | None = None
    adj_lower_share: float | None = None
    adj_upper_share: float | None = None
    lower_share: float | None = None
    upper_share: float | None = None
    real_lower_share: float | None
    real_average_share: float | None
    real_upper_share: float | None
    active: bool


# %%


def fetch_data(target_company: str):
    with open(f"data/{target_company}.json", "r") as f:
        data = json.load(f)
    return [OwnershipNode(**d) for d in data]


# Takes the share interval expressed as a string in the raw data and converts it to an interval of floats.
def parse_share_interval(network: list[OwnershipNode]):
    for n in range(len(network)):
        share_string = network[n].share.replace("%", "")
        if "-" in share_string:
            lower_share, upper_share = share_string.split("-")
        elif "<" in share_string:
            lower_share = 0.0001
            upper_share = share_string.replace("<", "")
        else:
            lower_share = share_string
            upper_share = share_string
        lower_share = float(lower_share) / 100
        upper_share = float(upper_share) / 100
        network[n].init_lower_share = lower_share
        network[n].init_upper_share = upper_share
    return network


# Adjusts the upper limit for all companies where the sum of the lower limits of the other owners exceeds the residual ownership.
def adjust_impossible_upper_limits(network: list[OwnershipNode]):
    for n in range(len(network)):
        owners: list[OwnershipNode] = []
        focus_target = network[n].target
        for m in range(len(network)):
            if network[m].target == focus_target:
                owners.append(network[m])
        for check_owner_m in range(len(owners)):
            sum_lower = 0
            for l in range(len(owners)):
                if owners[l].source_name != owners[check_owner_m].source_name:
                    sum_lower += owners[l].init_lower_share
            if sum_lower + owners[check_owner_m].init_upper_share > 1:
                owners[check_owner_m].init_upper_share = 1 - sum_lower
        for m in range(len(owners)):
            for l in range(len(network)):
                if network[l].id == owners[m].id:
                    network[l].init_upper_share = round(owners[m].init_upper_share, 2)
    return network


# Recursively finds all circular ownerships related directly or indirectly to the current node.
def find_circular_ownerships_of_current_node(
    current_source: int,
    network: list[OwnershipNode],
    circ_owners: list[OwnershipNode],
    last_source: int | None = None,
):
    nodes_w_current_source_as_source = []
    for m in range(len(network)):
        if network[m].source == current_source:
            nodes_w_current_source_as_source.append(network[m])
    for m in range(len(nodes_w_current_source_as_source)):
        for l in range(len(network)):
            if (
                network[l].source == nodes_w_current_source_as_source[m].target
                and network[l].target == current_source
            ):
                circ_owners.append(network[l])
                if network[l].source != last_source:
                    circ_owners = find_circular_ownerships_of_current_node(
                        network[l].source, network, circ_owners, current_source
                    )
    return circ_owners


# Removes all circular ownerships that are not directly related to the current node.
def check_if_all_circular_owners_are_related_to_current_node(
    current_source: int,
    circ_owners: list[OwnershipNode],
):
    unique_owners = set()
    for n in range(len(circ_owners)):
        unique_owners.add(circ_owners[n].source)
    for owner in unique_owners:
        if owner != current_source:
            related = False
            for n in range(len(circ_owners)):
                if (
                    circ_owners[n].source == owner
                    and circ_owners[n].target == current_source
                ):
                    related = True
            if not related:  # Remove all entries with owner as source and target
                for n in range(len(circ_owners) - 1, 0, -1):
                    if circ_owners[n].source == owner or circ_owners[n].target == owner:
                        circ_owners.remove(circ_owners[n])
    return circ_owners


# Creates the index and column ids for the ownership matrix. Also creates a set of unique circular owners.
def create_matrix_index_and_unique_owners(circ_owners: list[OwnershipNode]):
    index = []
    unique_owners = set()
    for owner in circ_owners:
        unique_owners.add(owner.source)
        index.append(str(owner.source))
        index.append(str(owner.source) + "_DUMMY")
    columns = index.copy()
    return index, columns, unique_owners


# Creates the ownership matrix from the circular ownerships.
def create_ownership_matrix(
    circ_owners: list[OwnershipNode], index: list[str], columns: list[str]
):
    df = pd.DataFrame([[0.0] * len(index)] * len(index), index=index, columns=columns)
    for i in index:
        for n in circ_owners:
            if i == str(n.source):
                df.loc[i, str(n.target)] = n.init_lower_share

    for owner in circ_owners:
        df.loc[str(owner.source) + "_DUMMY", str(owner.source)] = (
            1 - df.loc[:, str(owner.source)].sum()
        )
        df.loc[str(owner.source) + "_DUMMY", str(owner.source) + "_DUMMY"] = 1
    return df


# Calculates the adjusted ownership matrix using the ownership matrix by
# squaring it in a finite loop until all values are stable to 4 decimal points.
def calculate_adjusted_ownership_matrix(
    df: pd.DataFrame, index: list[str], columns: list[str]
):
    stable = False
    df_adj = df.copy()

    while not stable:
        stable = True
        df_adj = df.dot(df_adj)
        for n in range(len(index)):
            for m in range(len(columns)):
                if abs(df_adj.iloc[n, m] - df.iloc[n, m]) > 0.0001:
                    stable = False
                else:
                    df = df_adj.copy()
        if stable:
            df_adj = df_adj.round(decimals=4)
            break
    return df_adj


# After finding the effective ownership between the circular owners. The share of the
# current node not owned by the circular owners is distributed to the other non-circular owners
# as [non-circular-effective-share]/[non-circular-direct-share]*[owner-direct-share].
# All circular owners are allocated their respective effective share found in the finite loop.
def calculate_adjusted_ownership_of_current_node(
    current_source: int,
    network: list[OwnershipNode],
    df_adj: pd.DataFrame,
    df_org: pd.DataFrame,
    unique_owners: set[int],
):
    for n in range(len(network)):
        if network[n].target == current_source:
            if network[n].source in unique_owners:
                network[n].adj_lower_share = df_adj.loc[
                    str(network[n].source) + "_DUMMY", str(network[n].target)
                ]
            else:
                network[n].adj_lower_share = (
                    df_adj.loc[str(current_source) + "_DUMMY", str(current_source)]
                    / df_org.loc[str(current_source) + "_DUMMY", str(current_source)]
                    * network[n].init_lower_share
                )
    return network


# Last preparation step before we can calculate the effective ownership.
# It makes sure all nodes have an adj. lower and upper limit to be used in calculating the effective ownership.
def calculate_upper_limit_from_circular_ownership_and_fill_nones(
    network: list[OwnershipNode],
):
    for n in range(len(network)):
        if network[n].adj_lower_share is not None:
            network[n].lower_share = network[n].adj_lower_share
            network[n].upper_share = (
                network[n].adj_lower_share
                * network[n].init_upper_share
                / network[n].init_lower_share
            )
        else:
            network[n].lower_share = network[n].init_lower_share
            network[n].upper_share = network[n].init_upper_share
    return network


# The main function of the module that adjusts the ownership shares for impossible upper limit shares and circular ownership.
def adjust_for_impossible_upper_limits_and_circular_ownerships(
    network: list[OwnershipNode],
):
    network = parse_share_interval(network)
    network = adjust_impossible_upper_limits(network)
    for n in range(len(network)):
        circ_owners: list[OwnershipNode] = []
        current_source = network[n].source
        circ_owners = find_circular_ownerships_of_current_node(
            current_source, network, circ_owners
        )
        circ_owners = check_if_all_circular_owners_are_related_to_current_node(
            current_source, circ_owners
        )
        index, columns, unique_owners = create_matrix_index_and_unique_owners(
            circ_owners
        )
        df_ownership = create_ownership_matrix(circ_owners, index, columns)
        if not df_ownership.empty:
            df_adj_ownership = calculate_adjusted_ownership_matrix(
                df_ownership.copy(), index, columns
            )
            network = calculate_adjusted_ownership_of_current_node(
                current_source,
                network,
                df_adj_ownership,
                df_ownership.copy(),
                unique_owners,
            )
        network = calculate_upper_limit_from_circular_ownership_and_fill_nones(network)
    return network
