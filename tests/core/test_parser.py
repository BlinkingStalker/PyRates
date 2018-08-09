"""Test suite for basic parser module functionality.
"""

# external imports
import numpy as np
import tensorflow as tf
import pytest

# pyrates internal imports
from pyrates.parser import NPExpressionParser, TFExpressionParser

# meta infos
__author__ = "Richard Gast, Daniel Rose"
__status__ = "Development"


###########
# Utility #
###########


def setup_module():
    print("\n")
    print("===============================")
    print("| Test Suite 1 : Parser Module |")
    print("===============================")


#########
# Tests #
#########

def test_1_1_expression_parser_init():
    """Testing initializations of different expression parsers:

    See Also
    --------
    :class:`ExpressionParser`: Detailed documentation of expression parser attributes and methods.
    :class:`NPExpressionParser`: Documentation of the numpy-based expression parser
    """

    parsers = [NPExpressionParser, TFExpressionParser]

    # test minimal minimal call example
    ###################################

    for Parser in parsers:
        parser = Parser("a + b", {'a': np.ones((3, 3)), 'b': 5.})
        assert isinstance(parser, Parser)


def test_1_2_expression_parser_parsing_exceptions():
    """Testing error handling of different erroneous parser instantiations:

    See Also
    --------
    :class:`ExpressionParser`: Detailed documentation of expression parser attributes and methods.
    :class:`LambdaExpressionParser`: Documentation of a non-symbolic expression parser.
    """

    parsers = [NPExpressionParser, TFExpressionParser]

    # test expected exceptions
    ##########################

    for Parser in parsers:

        # undefined variables
        with pytest.raises(ValueError):
            Parser("a + b", {}).parse_expr()()

        # wrong dimensionality of dictionary arguments
        with pytest.raises(ValueError):
            Parser("a + b", {'a': np.ones((3, 3)), 'b': np.ones((4, 4))}).parse_expr()()

        # wrong data type of dictionary arguments
        with pytest.raises(TypeError):
            Parser("bool(a) + float32(b)", {'a': np.ones((3, 3)), 'b': np.ones((3, 3))}).parse_expr()()

        # undefined mathematical operator
        with pytest.raises(ValueError):
            Parser("a $ b", {'a': np.ones((3, 3)), 'b': 5.}).parse_expr()()

        # undefined function
        with pytest.raises(ValueError):
            Parser("a / b(5.)", {'a': np.ones((3, 3)), 'b': 5.}).parse_expr()()


def test_1_3_expression_parser_math_ops():
    """Testing handling of mathematical operations by expression parsers:

    See Also
    --------
    :class:`ExpressionParser`: Detailed documentation of expression parser attributes and methods.
    :class:`LambdaExpressionParser`: Documentation of a non-symbolic expression parser.
    """

    # define test cases
    math_expressions = [("4 + 5", 9.),                # simple addition
                        ("4 - 5", -1.),               # simple subtraction
                        ("4. * 5.", 20.),             # simple multiplication
                        ("4. / 5.", 0.8),             # simple division
                        ("4.^2", 16.),                # simple exponentiation
                        ("4 + -5", -1.),              # negation of variable
                        ("4 * -2", -8.),              # negation of variable in higher-order operation
                        ("4 + 5 * 2", 14.),           # multiplication before addition
                        ("(4 + 5) * 2", 18.),         # parentheses before everything
                        ("4 * 5^2", 100.)             # exponentiation before multiplication
                        ]

    # test expression parsers on expression results
    ###############################################

    for expr, target in math_expressions:

        # numpy-based parser
        result = NPExpressionParser(expr_str=expr, args={}).parse_expr()()
        assert result == pytest.approx(target, rel=1e-6)

        # tensorflow-based parser
        gr = tf.get_default_graph()
        with gr.as_default():
            result = TFExpressionParser(expr_str=expr, args={}, tf_graph=gr).parse_expr()
        with tf.Session(graph=gr) as sess:
            sess.run(result)
            result = result.eval()
        assert result == pytest.approx(target, rel=1e-6)


def test_1_4_expression_parser_logic_ops():
    """Testing handling of logical operations by expression parsers:

    See Also
    --------
    :class:`ExpressionParser`: Detailed documentation of expression parser attributes and methods.
    :class:`LambdaExpressionParser`: Documentation of a non-symbolic expression parser.
    """

    # define test cases
    logic_expressions = ["4 == 4",                # simple equals
                         "4 != 5",                # simple not-equals
                         "4 < 5",                 # simple less
                         "5 > 4",                 # simple larger
                         "4 <= 4",                # less equals I
                         "4 <= 5",                # less equals II
                         "5 >= 5",                # larger equals I
                         "5 >= 4",                # larger equals II
                         ]

    # test expression parsers on expression results
    ###############################################

    for expr in logic_expressions:

        # numpy-based parser
        assert NPExpressionParser(expr_str=expr, args={}).parse_expr()()

        # tensorflow-based parser
        gr = tf.get_default_graph()
        with gr.as_default():
            result = TFExpressionParser(expr_str=expr, args={}, tf_graph=gr).parse_expr()
        with tf.Session(graph=gr) as sess:
            sess.run(result)
            assert result.eval()

    # test false logical expression for either parser
    #################################################

    expr = "5 >= 6"
    assert NPExpressionParser(expr_str=expr, args={}).parse_expr()() == False

    # tensorflow-based parser
    gr = tf.get_default_graph()
    with gr.as_default():
        result = TFExpressionParser(expr_str=expr, args={}, tf_graph=gr).parse_expr()
    with tf.Session(graph=gr) as sess:
        sess.run(result)
        assert result.eval() == False


def test_1_5_expression_parser_indexing():
    """Testing handling of indexing operations by expression parsers:

    See Also
    --------
    :class:`ExpressionParser`: Detailed documentation of expression parser attributes and methods.
    :class:`LambdaExpressionParser`: Documentation of a non-symbolic expression parser.
    """

    A = np.random.randn(10, 10)
    B = np.eye(10) == 1

    # define valid test cases
    #########################

    indexed_expressions = [("A[:]", A[:]),               # single-dim indexing I
                           ("A[0]", A[0]),               # single-dim indexing II
                           ("A[-2]", A[-2]),             # single-dim indexing III
                           ("A[0:5]", A[0:5]),           # single-dim slicing I
                           ("A[-1:0:-1]", A[-1:0:-1]),   # single-dim slicing II
                           ("A[4,5]", A[4, 5]),          # two-dim indexing I
                           ("A[5,0:-2]", A[5, 0:-2]),    # two-dim indexing II
                           ("A[A > 0]", A[A > 0]),       # boolean indexing
                           ("A[B]", A[np.where(B)]),     # indexing with other array
                           ("A[int64(2 * 2):8 - 1]",
                            A[(2 * 2):8 - 1]),           # using expressions as indices
                           ]

    # test expression parsers on expression results
    ###############################################

    for expr, target in indexed_expressions:

        # numpy-based parser
        result = NPExpressionParser(expr_str=expr, args={'A': A, 'B': np.where(B)}).parse_expr()()
        assert result == pytest.approx(target, rel=1e-6)

        # tensorflow-based parser
        gr = tf.get_default_graph()
        with gr.as_default():
            result = TFExpressionParser(expr_str=expr, args={'A': tf.constant(A), 'B': tf.constant(np.argwhere(B))},
                                        tf_graph=gr).parse_expr()
        with tf.Session(graph=gr) as sess:
            sess.run(result)
            result = result.eval()
        assert result == pytest.approx(target, rel=1e-6)

    # define invalid test cases
    ###########################

    indexed_expressions_wrong = ["A[1.2]",       # single-dim indexing I
                                 "A[all]",       # single-dim indexing II
                                 "A[-11]",       # single-dim indexing III
                                 "A[0:5:2:1]",   # single-dim slicing I
                                 "A[-1::0:-1]",  # single-dim slicing II
                                 ]

    # test expression parsers on expression results
    ###############################################

    for expr in indexed_expressions_wrong:
        # numpy-based parser
        with pytest.raises((IndexError, ValueError, SyntaxError, TypeError)):
            NPExpressionParser(expr_str=expr, args={'A': A, 'B': np.where(B)}).parse_expr()()

        # tensorflow-based parser
        gr = tf.get_default_graph()
        with gr.as_default():
            with pytest.raises((IndexError, ValueError, SyntaxError, TypeError)):
                TFExpressionParser(expr_str=expr, args={'A': tf.constant(A), 'B': tf.constant(np.argwhere(B))},
                                   tf_graph=gr).parse_expr()


def test_1_6_expression_parser_funcs():
    """Testing handling of function calls by expression parsers:

    See Also
    --------
    :class:`ExpressionParser`: Detailed documentation of expression parser attributes and methods.
    :class:`LambdaExpressionParser`: Documentation of a non-symbolic expression parser.
    """

    A = np.random.randn(10, 10)

    # define valid test cases
    #########################

    expressions = [("abs(5.)", 5.),              # simple function call
                   ("abs(-5.)", 5.),             # function call of negative arg
                   ("abs(4 * -2 + 1)", 7.),       # function call on mathematical expression
                   ("int64(4 > 5)", 0),          # function call on boolean expression
                   ("abs(A[A > 0])",
                    np.abs(A[A > 0])),           # function call on indexed variable
                   ("abs(sin(1.5))",
                    np.abs(np.sin(1.5))),        # nested function calls
                   ]

    # test expression parsers on expression results
    ###############################################

    for expr, target in expressions:

        # numpy-based parser
        result = NPExpressionParser(expr_str=expr, args={'A': A}).parse_expr()
        if callable(result):
            result = result()
        assert result == pytest.approx(target, rel=1e-6)

        # tensorflow-based parser
        gr = tf.get_default_graph()
        with gr.as_default():
            result = TFExpressionParser(expr_str=expr, args={'A': tf.constant(A)}, tf_graph=gr).parse_expr()
        with tf.Session(graph=gr) as sess:
            sess.run(result)
            result = result.eval()
        assert result == pytest.approx(target, rel=1e-6)

    # define invalid test cases
    ###########################

    expressions_wrong = ["abs((4.)",       # wrong parentheses I
                         "abs[4.]",        # wrong parentheses II
                         "abs(0. True)",   # no comma separation on arguments
                         "abs(0.,1,5,3)",  # wrong argument number
                         ]

    # test expression parsers on expression results
    ###############################################

    for expr in expressions_wrong:
        # numpy-based parser
        with pytest.raises((IndexError, ValueError, SyntaxError, TypeError)):
            NPExpressionParser(expr_str=expr, args={'A': A}).parse_expr()()

        # tensorflow-based parser
        gr = tf.get_default_graph()
        with gr.as_default():
            with pytest.raises((IndexError, ValueError, SyntaxError, TypeError)):
                TFExpressionParser(expr_str=expr, args={'A': tf.constant(A)},
                                   tf_graph=gr).parse_expr()
