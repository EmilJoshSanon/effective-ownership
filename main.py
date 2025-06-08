# Problem description:
# Find the effective ownership in focus company (CasaAS and ResightsApS) for each company in the ownership structure.

# NOTES:
# 1. All companies related to focus company has a source-target relationship that will eventually lead to the focus company.
#    Therefore, easier to start from the focus company and work our way backwards.
# 2. Be aware that two companies can own shares in eachother.
# 3. Example: A and B owns each 50% in C. C owns 50% in A. Effectively, 50% of A's ownership in C are shares C owns in itself and those shares will be distributed pro-rata to A and B.
#    Accordingly, the effective ownership of A in C is 37.5% (25% + 25% * 50%) and B in C is 62.5% (50% + 25% * 50%).
# 4. There seem to be three different ways an ownership can be stated in the json files; <5%, lower-upper%, and 100%. Since we
#    we don't know the lower bound when <5% we will set it to 0%, such that <5% gets translated to lower_share=0% and upper_share=5%.
# 5. Some entries in the json files are inactive. They just add noise and will therefore be remove.
# 6. If one company has two effective owerships of the focus company, the two effective ownerships can just be added together to get the total effective ownership.

import json
import pydantic


class OwnershipNode(pydantic.BaseModel):
    id: str
    source: int
    source_name: str
    source_depth: int
    target: int
    target_name: str
    target_depth: int
    share: str
    real_lower_share: float | None
    real_average_share: float | None
    real_upper_share: float | None
    active: bool


class Share(pydantic.BaseModel):
    lower_share: float
    average_share: float
    upper_share: float


def fetch_data(target_company: str):
    with open(f"data/{target_company}.json", "r") as f:
        data = json.load(f)
    return [OwnershipNode.model_validate(d) for d in data]


def parse_share_interval(share_string: str):
    share_string = share_string.replace("%", "")
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
    average_share = (lower_share + upper_share) / 2
    return Share(
        lower_share=lower_share, average_share=average_share, upper_share=upper_share
    )


def check_for_circular_ownership(
    source_name: str, target_name: str, network: list[OwnershipNode]
):
    circular_ownership = False
    for m in range(len(network)):
        if (
            network[m].source_name == target_name
            and network[m].target_name == source_name
            and network[m].active
        ):
            circular_ownership = True
    return circular_ownership


def calculate_circular_ownership(source_share: Share, target_share: Share):
    def calculator(source_share: float, target_share: float):
        direct_ownership = source_share * (1 - target_share)
        pro_rata_ownership = source_share**2 * target_share
        return direct_ownership + pro_rata_ownership

    source_share.lower_share = calculator(
        source_share.lower_share, target_share.lower_share
    )
    source_share.average_share = calculator(
        source_share.average_share, target_share.average_share
    )
    source_share.upper_share = calculator(
        source_share.upper_share, target_share.upper_share
    )
    return source_share


def calculate_effective_ownership(
    source_share: Share, current_node: OwnershipNode, previous_node: OwnershipNode
):
    # If real share is None, set it to 0. Otherwise we can't add to it.
    # Which is necessary if a subsidiary down the line has two effective ownerships of the focus company.
    current_node.real_lower_share = (
        0 if current_node.real_lower_share is None else current_node.real_lower_share
    )
    current_node.real_average_share = (
        0
        if current_node.real_average_share is None
        else current_node.real_average_share
    )
    current_node.real_upper_share = (
        0 if current_node.real_upper_share is None else current_node.real_upper_share
    )

    current_node.real_lower_share += (
        source_share.lower_share * previous_node.real_lower_share
    )
    current_node.real_average_share += (
        source_share.average_share * previous_node.real_average_share
    )
    current_node.real_upper_share += (
        source_share.upper_share * previous_node.real_upper_share
    )
    return current_node


# Algorithm:
# 1. If an entry has target_company
# 2. -> Extract share interval from share string
# 3. -> If previous_node is None => we're at root, hence save share of node in real share
# 4. -> If not: Check if there is a circular ownership
# 5. -> If so: Calculate circular ownership
# 6. -> If not: Calculate effective ownership without circular ownership.
def populate_effective_ownership(
    target_company: str,
    network: list[OwnershipNode],
    previous_node: OwnershipNode | None = None,
):
    if previous_node:
        previous_target_name = previous_node.target_name
    else:
        previous_target_name = ""
    result_network = network.copy()
    for n in range(len(network)):
        # Check if this is a circular ownership to prevent infinity recursion.
        if (
            previous_target_name != network[n].source_name
            and network[n].target_name == target_company
            and network[n].active
        ):
            source_share = parse_share_interval(network[n].share)
            if previous_node:
                # Check if a node exist with source_name equal to the current nodes target_name
                # and target_name equal to the current nodes source_name. If so, it means there is a
                # circular ownership and we therefore need to account for that.
                for m in range(len(network)):
                    if (
                        network[m].source_name == network[n].target_name
                        and network[m].target_name == network[n].source_name
                    ):
                        target_share = parse_share_interval(network[m].share)
                        source_share = calculate_circular_ownership(
                            source_share, target_share
                        )
                result_network[n] = calculate_effective_ownership(
                    source_share, network[n], previous_node
                )
            else:
                # No previous node means we are at the root of the tree
                result_network[n].real_lower_share = source_share.lower_share
                result_network[n].real_average_share = source_share.average_share
                result_network[n].real_upper_share = source_share.upper_share

            result_network = populate_effective_ownership(
                network[n].source_name, result_network, result_network[n]
            )
    return result_network


if __name__ == "__main__":
    for target_company in [
        {"comp_name": "CASA A/S", "file_name": "CasaAS"},
        {"comp_name": "Resights ApS", "file_name": "ResightsApS"},
    ]:
        network = fetch_data(target_company["file_name"])
        result_network = populate_effective_ownership(
            target_company["comp_name"], network
        )
        with open(f"result/{target_company['file_name']}_result.json", "w") as f:
            json.dump(
                [node.model_dump() for node in result_network],
                f,
                indent=4,
                ensure_ascii=False,
            )
