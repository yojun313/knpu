def clean_doc(doc: dict, stringify_id=True) -> dict:
    if "_id" in doc:
        del doc["_id"]
    return doc
