from luigi.freezing import FrozenOrderedDict


def unfreeze(config):
    """
    unfreeze the dictionary that is frozen to serialize it
    and send it from one luigi task to another
    """
    try:
        unfrozen_dict = {}
        for key in config.keys():
            unfrozen_dict[key] = unfreeze(config[key])
        return unfrozen_dict
    except AttributeError:
        try:
            unfrozen_list = []
            if not isinstance(config, str):
                for elem in config:
                    unfrozen_list.append(unfreeze(elem))
                return unfrozen_list
            return config
        except TypeError:
            return config


def test_unfreeze():
    input_dict = FrozenOrderedDict({'a': 1, 'b': (1, 2, 3),
                                    'd': FrozenOrderedDict({'e': 4})})
    expected_dict = {'a': 1, 'b': [1, 2, 3],
                     'd': {'e': 4}}
    assert expected_dict == unfreeze(input_dict)
