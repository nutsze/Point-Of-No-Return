"""Terminal runner for the visual novel: character creation, node loop,
ending screen with the real-people dedication credits.
"""
from __future__ import annotations

import sys
import textwrap

from . import state as state_mod
from .story import DEDICATION, ENDINGS, NODES, PEOPLE, START_NODE, compute_ending

WIDTH = 72
PROFESSIONS = ["Студент(ка)", "Врач", "Учитель(ница)", "IT-специалист(ка)",
               "Продавец(щица)", "Инженер(ка)"]
CITIES = ["Москва", "Санкт-Петербург", "Екатеринбург", "Новосибирск",
          "Томск", "Краснодар", "Казань", "Владивосток"]


def wrap(text: str) -> str:
    paragraphs = text.split("\n\n")
    return "\n\n".join(textwrap.fill(p, WIDTH) for p in paragraphs)


def rule(char="─"):
    print(char * WIDTH)


def pick(prompt: str, options: list[str]) -> str:
    while True:
        print(prompt)
        for i, opt in enumerate(options, 1):
            print(f"  {i}. {opt}")
        raw = input("> ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print("Не понял выбор, попробуй ещё раз.\n")


def ask_text(prompt: str) -> str:
    while True:
        raw = input(prompt + "\n> ").strip()
        if raw:
            return raw
        print("Нужно что-то ввести.\n")


def character_creation() -> state_mod.State:
    s = state_mod.State()
    rule("═")
    print("TEN WINTERS".center(WIDTH))
    print("2020-2030 · вымышленный герой на фоне реальной истории".center(WIDTH))
    rule("═")
    print()
    s.name = ask_text("Как тебя зовут?")
    print()
    s.profession = pick("Кем ты работаешь?", PROFESSIONS)
    print()
    s.city = pick("В каком городе живёшь?", CITIES)
    print()
    return s


def show_node(s: state_mod.State, node_id: str) -> str | None:
    node = NODES[node_id]
    rule()
    print(f"{node['date']}  ·  {s.format(node['place'])}")
    rule()
    print()
    print(wrap(s.format(node["text"])))
    print()
    if node.get("source"):
        print(wrap("[источник] " + node["source"]))
        print()
    choices = node["choices"]
    for i, (label, tag, _next, _fx) in enumerate(choices, 1):
        tagstr = f" ({tag})" if tag else ""
        print(f"  {i}. {label}{tagstr}")
    print()
    while True:
        raw = input("Выбор > ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(choices):
            _label, _tag, nxt, fx = choices[int(raw) - 1]
            if fx:
                fx(s)
            return nxt(s) if callable(nxt) else nxt
        print("Такого варианта нет, попробуй ещё раз.")


def show_ending(s: state_mod.State) -> None:
    kind = compute_ending(s)
    ending = ENDINGS[kind]
    print()
    rule("═")
    print(ending["headline"].center(WIDTH))
    print(ending["sub"].center(WIDTH))
    rule("═")
    print()
    print(f"2030 · Российская Федерация".center(WIDTH))
    print("Президент: ?".center(WIDTH))
    print(f"{s.name}, {s.profession}, {s.city}".center(WIDTH))
    print()
    print(wrap(s.format(ending["note"])))
    print()
    if ending["show_dedication"]:
        rule()
        print("ЗА ВАС БОРОЛИСЬ".center(WIDTH))
        rule()
        for line in DEDICATION:
            print(f"  {line}")
        print()
        print(f"  {s.name} — {s.profession}, {s.city}")
        print()
        print(wrap(
            "Это вымышленная история и вымышленный персонаж. Люди выше — реальные "
            "общественные деятели, журналисты и правозащитники; список — дань "
            "уважения, а не часть сюжета, и не подразумевает их участия в этой истории."
        ))
    rule("═")


def show_codex() -> None:
    rule()
    print("ДОСЬЕ: РЕАЛЬНЫЕ ЛЮДИ В ЭТОЙ ИГРЕ".center(WIDTH))
    rule()
    for p in PEOPLE:
        mark = " †" if p["died"] else ""
        print(f"\n{p['name']}{mark} ({p['years']})")
        print(wrap(p["bio"]))
    print()


def main() -> None:
    saved = state_mod.load()
    if saved:
        choice = pick(
            "Найдено сохранение. Продолжить или начать заново?",
            ["Продолжить", "Начать заново"],
        )
        if choice == "Продолжить":
            s = saved
        else:
            state_mod.clear()
            s = character_creation()
    else:
        s = character_creation()

    node_id = s.node
    while node_id != "FINALE":
        node_id = show_node(s, node_id)
        s.node = node_id
        state_mod.save(s)

    show_ending(s)
    state_mod.clear()

    again = pick("Что дальше?", ["Посмотреть досье реальных людей", "Выйти"])
    if again.startswith("Посмотреть"):
        show_codex()


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\n\nДо встречи.")
        sys.exit(0)
