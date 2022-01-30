import re

from src.ml.action.set.set import Set
from src.ml.action.feature.feature import Feature


class Regex(Set):
    def __init__(self, regex, text, value_type='str', **kwargs):
        super().__init__(**kwargs)
        self.regex = regex
        self.text = text
        self.value_type = value_type

    str_to_type = {'str': str, 'int': int, 'float': float, 'bool': bool}

    def post_call(self, action=None, *args, **kwargs):
        if isinstance(action, Feature):
            if self.regex is None or self.text is None:
                v = None
            else:
                r = re.findall(self.regex, self.text)
                t = self.str_to_type[self.value_type]
                if len(r) == 0:
                    v = None
                elif len(r) == 1:
                    v = t(r[0].strip())
                else:
                    v = [t(x.strip()) for x in r]
            action.value = v
        return self, action
