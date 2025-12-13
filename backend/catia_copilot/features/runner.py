from .register_features import registry

def run_feature(feature_name, **kwargs):
    handler = registry.get_handler(feature_name)
    if not handler:
        return {"error": f"Feature '{feature_name}' not found."}
    
    try:
        # Assuming handler is a function or callable class
        result = handler(**kwargs)
        return {"status": "success", "result": result}
    except Exception as e:
        return {"error": str(e)}
