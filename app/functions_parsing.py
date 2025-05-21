from tree_sitter import Language, Parser
import os

from config import parser_cfg

LIB_PATH = parser_cfg['BUILD_PATH']

if not os.path.exists(LIB_PATH):
    Language.build_library(
        LIB_PATH,
        [parser_cfg['LIB_PATH']]
    )

CPP_LANGUAGE = Language(LIB_PATH, 'cpp')


def parse_cpp_code(code: str):
    """
    Parse C++ code and returns AST.
    """
    parser = Parser()
    parser.set_language(CPP_LANGUAGE)
    
    tree = parser.parse(code.encode('utf8'))
    return tree.root_node


def print_tree(node, indent=0):
    """
    Print AST correctly.
    """
    print('  ' * indent + f"{node.type} [{node.start_point} - {node.end_point}]")
    for child in node.children:
        print_tree(child, indent + 1)


if __name__ == '__main__':
    cpp_file_path = '../test/parsing_tests/finance_pricing_engine.cpp'
    with open(cpp_file_path, 'r') as file:
        cpp_code = file.read()

    root = parse_cpp_code(cpp_code)
    print_tree(root)
