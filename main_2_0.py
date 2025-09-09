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
    real_lower_share: float | None
    real_average_share: float | None
    real_upper_share: float | None
    active: bool


class Share(pydantic.BaseModel):
    lower_share: float
    average_share: float
    upper_share: float


# %%


def fetch_data(target_company: str):
    with open(f"data/{target_company}.json", "r") as f:
        data = json.load(f)
    return [OwnershipNode(**d) for d in data]


def parse_share_interval(network: list[OwnershipNode]):
    for n in range(len(network)):
        share_string = network[n].share.replace("%", "")
        if "-" in share_string:
            lower_share, upper_share = share_string.split("-")
        elif "<" in share_string:
            lower_share = 0
            upper_share = share_string.replace("<", "")
        else:
            lower_share = share_string
            upper_share = share_string
        lower_share = float(lower_share) / 100
        upper_share = float(upper_share) / 100
        network[n].init_lower_share = lower_share if lower_share > 0 else 0.0001
        network[n].init_upper_share = upper_share
    return network


def adjust_upper_limits(network: list[OwnershipNode]):
    for n in range(len(network)):
        owners = []
        check_source = network[n].source_name
        for m in range(len(network)):
            if network[m].target_name == check_source:
                owners.append(network[m])
        for m in range(len(owners)):
            check_owner_m = m
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


def create_matrix_index_and_unique_owners(circ_owners: list[OwnershipNode]):
    index = []
    unique_owners = set()
    for owner in circ_owners:
        unique_owners.add(owner.source)
        index.append(str(owner.source))
        index.append(str(owner.source) + "_DUMMY")
    columns = index.copy()
    return index, columns, unique_owners


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


def find_circular_ownerships(network: list[OwnershipNode]):
    network = parse_share_interval(network)
    network = adjust_upper_limits(network)
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
    return network


# %%
network = fetch_data("CasaAS")
network = find_circular_ownerships(network)

# todo
# 1. Calculate adj upper limit as adj_lower * init_upper_limit / init_lower_limit
# 2. Create lower/upper_share = adj_lower/upper if not none else init_lower/upper

# %%
for n in network:
    if n.target == 38235036:
        print(n)
