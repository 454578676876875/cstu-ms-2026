def slugify(text):
    return text.strip().lower().replace(" ", "-")


def truncate(text, max_len):
    return text if len(text) <= max_len else text[:max_len] + "..."
