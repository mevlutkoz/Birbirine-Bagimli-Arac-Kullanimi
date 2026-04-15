"""Interactive CLI for the payment support agent."""

import logging
import sys

from agent.orchestrator import Orchestrator


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)-28s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler("agent.log", mode="a", encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )


def main() -> None:
    setup_logging()
    logger = logging.getLogger(__name__)

    print("=" * 50)
    print("  Payment Support Agent")
    print("  Type 'quit' to exit, 'reset' to start over")
    print("=" * 50)

    orchestrator = Orchestrator()

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break
        if user_input.lower() == "reset":
            orchestrator.reset()
            print("(conversation reset)")
            continue

        logger.info("User input received: %s", user_input)
        response = orchestrator.handle_message(user_input)
        print(f"\nAgent: {response}")


if __name__ == "__main__":
    main()
