from tree_sitter import Language, Parser
import os

# Chargement ou compilation du langage C++
LIB_PATH = 'build/my-languages.so'

if not os.path.exists(LIB_PATH):
    Language.build_library(
        LIB_PATH,
        ['tree-sitter-cpp']
    )

CPP_LANGUAGE = Language(LIB_PATH, 'cpp')


def parse_cpp_code(code: str) -> str:
    """
    Parse du code C++ et retourne l'AST sous forme de S-expression.
    """
    parser = Parser()
    parser.set_language(CPP_LANGUAGE)
    
    tree = parser.parse(code.encode('utf8'))
    return tree.root_node


def print_tree(node, indent=0):
    print('  ' * indent + f"{node.type} [{node.start_point} - {node.end_point}]")
    for child in node.children:
        print_tree(child, indent + 1)


if __name__ == '__main__':
    cpp_code = """
    int main() {
        int a = 5;
        return a;
    }
    """
    root = parse_cpp_code(cpp_code)
    print_tree(root)
