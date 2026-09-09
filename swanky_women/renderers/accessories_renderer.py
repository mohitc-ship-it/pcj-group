def normalize_accessories(accessories, total_rows=8):
    empty = {
        "description": "",
        "qty": "",
        "color": "",
        "position": ""
    }
    return accessories + [empty] * (total_rows - len(accessories))
