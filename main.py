"""Точка входа в игру и журнал критических ошибок."""
import traceback


def main() -> None:
    try:
        from game.app import main as run_game
        run_game()
    except Exception:
        from engine import save_directory
        (save_directory() / "crash.log").write_text(traceback.format_exc(), encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
