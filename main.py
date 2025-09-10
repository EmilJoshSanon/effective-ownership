# %%
import json
import pydantic
from adjust_direct_ownership import (
    adjust_for_impossible_upper_limits_and_circular_ownerships,
    OwnershipNode,
)


class ResultOwnerNode(pydantic.BaseModel):
    source: int
    source_name: str
    target: int
    target_name: str
    real_lower_share: float
    real_upper_share: float
    real_average_share: float


class FocusCompany(pydantic.BaseModel):
    id: int
    name: str


def fetch_data(target_company: str):
    with open(f"data/{target_company}.json", "r") as f:
        data = json.load(f)
    return [OwnershipNode.model_validate(d) for d in data]


def remove_inactive_nodes(network: list[OwnershipNode]):
    return [node for node in network if node.active]


def calculate_effective_ownership(
    source: OwnershipNode, current_node: OwnershipNode, previous_node: OwnershipNode
):
    # If real share is None, set it to 0. Otherwise we can't add to it.
    # Which is necessary if a subsidiary down the line has two effective ownerships of the focus company.
    current_node.real_lower_share = (
        0 if current_node.real_lower_share is None else current_node.real_lower_share
    )
    current_node.real_upper_share = (
        0 if current_node.real_upper_share is None else current_node.real_upper_share
    )

    current_node.real_lower_share += source.lower_share * previous_node.real_lower_share
    current_node.real_upper_share += source.upper_share * previous_node.real_upper_share
    current_node.real_average_share = (
        current_node.real_lower_share + current_node.real_upper_share
    ) / 2
    return current_node


def find_focus_company(
    network: list[OwnershipNode], focus_company_name: str
) -> FocusCompany | None:
    for node in network:
        if node.target_name == focus_company_name:
            return FocusCompany(
                id=node.target,
                name=node.target_name,
            )
    return None


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
            source = network[n]
            if previous_node:
                result_network[n] = calculate_effective_ownership(
                    source, network[n], previous_node
                )
            else:
                # No previous node means we are at the root of the tree
                result_network[n].real_lower_share = source.lower_share
                result_network[n].real_upper_share = source.upper_share
                result_network[n].real_average_share = (
                    source.lower_share + source.upper_share
                ) / 2

            result_network = populate_effective_ownership(
                network[n].source_name, result_network, result_network[n]
            )
    return result_network


# %%
if __name__ == "__main__":
    for target_company in [
        {"comp_name": "CASA A/S", "file_name": "CasaAS"},
        {"comp_name": "Resights ApS", "file_name": "ResightsApS"},
    ]:
        network = fetch_data(target_company["file_name"])
        focus_company = find_focus_company(network, target_company["comp_name"])
        network = remove_inactive_nodes(network)
        network = adjust_for_impossible_upper_limits_and_circular_ownerships(network)
        network = populate_effective_ownership(target_company["comp_name"], network)
        result_network: list[ResultOwnerNode] = []
        for node in network:
            owner_already_in_result = False
            if node.real_lower_share is not None:
                for owner in result_network:
                    if owner.source == node.source:
                        owner.real_lower_share += node.real_lower_share or 0
                        owner.real_upper_share += node.real_upper_share or 0
                        owner.real_average_share += node.real_average_share or 0
                        owner_already_in_result = True
                        break
                if not owner_already_in_result:
                    result_network.append(
                        ResultOwnerNode(
                            source=node.source,
                            source_name=node.source_name,
                            target=focus_company.id,
                            target_name=focus_company.name,
                            real_lower_share=node.real_lower_share,
                            real_upper_share=node.real_upper_share,
                            real_average_share=node.real_average_share,
                        )
                    )
        with open(f"result/{target_company['file_name']}_result.json", "w") as f:
            json.dump(
                [node.model_dump() for node in result_network],
                f,
                indent=4,
                ensure_ascii=False,
            )
