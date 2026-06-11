def safe_print(text):

    text = str(text)

    # replace problematic unicode characters
    text = text.replace("\u202f", " ")
    text = text.replace("\u00a0", " ")
    text = text.replace("≈", "->")

    print(
        text.encode("ascii", "replace").decode("ascii")
    )