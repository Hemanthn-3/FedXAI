"""Hospital 1 Flower client entrypoint."""

from hospital_nodes.client import run_node_from_args


def main() -> None:
    run_node_from_args("hospital_1", "hospital_nodes/node_1/data.csv")


if __name__ == "__main__":
    main()
