
class FeatureRegistry:
    def __init__(self):
        self.features = {}

    def register(self, name, handler):
        self.features[name] = handler
        print(f"Registered feature: {name}")

    def get_handler(self, name):
        return self.features.get(name)

registry = FeatureRegistry()
