"""Hospital 2 Flower client entrypoint."""

from hospital_nodes.client import run_node_from_args


def main() -> None:
    run_node_from_args("hospital_2", "hospital_nodes/node_2/data.csv")


if __name__ == "__main__":
    main()
