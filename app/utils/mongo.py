from bson import ObjectId

def serialize_mongo(obj):
    """
    Recursively convert Mongo ObjectId to str
    so FastAPI can JSON-encode safely.
    """
    if isinstance(obj, ObjectId):
        return str(obj)

    if isinstance(obj, list):
        return [serialize_mongo(i) for i in obj]

    if isinstance(obj, dict):
        return {k: serialize_mongo(v) for k, v in obj.items()}

    return obj
