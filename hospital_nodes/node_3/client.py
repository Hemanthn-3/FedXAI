"""Hospital 3 Flower client entrypoint."""

from hospital_nodes.client import run_node_from_args


def main() -> None:
    run_node_from_args("hospital_3", "hospital_nodes/node_3/data.csv")


if __name__ == "__main__":
    main()
