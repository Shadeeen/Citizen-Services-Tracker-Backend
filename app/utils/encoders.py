from bson import ObjectId

def objectid_encoder(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
    return obj
