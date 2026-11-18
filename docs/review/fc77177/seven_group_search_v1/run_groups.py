from search_batch import BASE, read, variant


def change(operator, action, old_frame, **fields):
    return {"type": "set", "operator": operator, "action": action, "frame": old_frame, "fields": fields}


FANG = "char_123_fang"
MEL = "char_208_melan"
MID = "char_283_midn"
SPOT = "char_284_spot"
ANSEL = "char_212_ansel"
HIBISC = "char_120_hibisc"


def main():
    groups = [
        ("G_MEL_ONLY", [change(MEL, "DEPLOY", 4155, tile=[4, 4], direction="RIGHT")]),
        ("G_FANG_ONLY", [change(FANG, "DEPLOY", 0, tile=[4, 5], direction="RIGHT")]),
        ("G_BOTH", [change(FANG, "DEPLOY", 0, tile=[4, 5], direction="RIGHT"), change(MEL, "DEPLOY", 4155, tile=[4, 4], direction="RIGHT")]),
        ("G_FANG_MELSWAP", [change(FANG, "DEPLOY", 0, tile=[4, 5], direction="RIGHT"), change(MEL, "DEPLOY", 4155, tile=[3, 5], direction="UP")]),
    ]
    for name, changes in groups:
        variant(name, changes, "Exchange one deployment responsibility group between independently verified baseline and complementary branch; observe new lane blocking and losses.")


if __name__ == "__main__":
    main()
