from tree_sitter import Language, Parser

Language.build_library(
  'build/my-languages.so',
  ['tree-sitter-cpp']
)

CPP_LANGUAGE = Language('build/my-languages.so', 'cpp')
