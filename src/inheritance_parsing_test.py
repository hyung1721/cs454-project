from src.core.parsing import parse_library, get_full_inheritance_dict


def find_max_inheritance_depth(inheritance_dict):
    cache = {}

    def dfs(class_path):
        if class_path in cache:
            return cache[class_path]

        if not inheritance_dict[class_path]:
            cache[class_path] = 0
            return 0

        max_depth = max(dfs(parent) for parent in inheritance_dict[class_path])
        cache[class_path] = max_depth + 1
        return max_depth + 1

    return max(dfs(cls) for cls in inheritance_dict)


if __name__ == '__main__':
    library_path = "./target_libraries/library_example1"
    node_container_dict = parse_library(library_path)

    full_inheritance_dict = get_full_inheritance_dict(node_container_dict)

    print(find_max_inheritance_depth(full_inheritance_dict))



