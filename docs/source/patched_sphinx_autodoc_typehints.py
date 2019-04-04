import inspect
import typing
from typing import get_type_hints, TypeVar, Any, AnyStr, Generic, Union

from sphinx.util import logging
from sphinx.util.inspect import Signature
from sphinx_autodoc_typehints import Protocol
import sphinx_autodoc_typehints


def format_annotation(annotation):
    if inspect.isclass(annotation) and annotation.__module__ == 'builtins':
        if annotation.__qualname__ == 'NoneType':
            return '``None``'
        else:
            return ':py:class:`{}`'.format(annotation.__qualname__)

    annotation_cls = annotation if inspect.isclass(annotation) else type(annotation)
    class_name = None
    if annotation_cls.__module__ == 'typing':
        params = None
        prefix = ':py:class:'
        module = 'typing'
        extra = ''

        if inspect.isclass(getattr(annotation, '__origin__', None)):
            annotation_cls = annotation.__origin__
            try:
                mro = annotation_cls.mro()
                if Generic in mro or (Protocol and Protocol in mro):
                    module = annotation_cls.__module__
            except TypeError:
                pass  # annotation_cls was either the "type" object or typing.Type

        if annotation is Any:
            return ':py:data:`~typing.Any`'
        elif annotation is AnyStr:
            return ':py:data:`~typing.AnyStr`'
        elif isinstance(annotation, TypeVar):
            return '\\%r' % annotation
        elif (annotation is Union or getattr(annotation, '__origin__', None) is Union or
              hasattr(annotation, '__union_params__')):
            prefix = ':py:data:'
            class_name = 'Union'
            if hasattr(annotation, '__union_params__'):
                params = annotation.__union_params__
            elif hasattr(annotation, '__args__'):
                params = annotation.__args__

            if params and len(params) == 2 and (hasattr(params[1], '__qualname__') and
                                                params[1].__qualname__ == 'NoneType'):
                class_name = 'Optional'
                params = (params[0],)
        elif annotation_cls.__qualname__ == 'Tuple' and hasattr(annotation, '__tuple_params__'):
            params = annotation.__tuple_params__
            if annotation.__tuple_use_ellipsis__:
                params += (Ellipsis,)
        elif annotation_cls.__qualname__ == 'Callable':
            prefix = ':py:data:'
            arg_annotations = result_annotation = None
            if hasattr(annotation, '__result__'):
                arg_annotations = annotation.__args__
                result_annotation = annotation.__result__
            elif getattr(annotation, '__args__', None):
                arg_annotations = annotation.__args__[:-1]
                result_annotation = annotation.__args__[-1]

            if arg_annotations in (Ellipsis, (Ellipsis,)):
                params = [Ellipsis, result_annotation]
            elif arg_annotations is not None:
                params = [
                    '\\[{}]'.format(
                        ', '.join(format_annotation(param) for param in arg_annotations)),
                    result_annotation
                ]
        elif hasattr(annotation, 'type_var'):
            # Type alias
            class_name = annotation.name
            params = (annotation.type_var,)
        elif getattr(annotation, '__args__', None) is not None:
            params = annotation.__args__
        elif hasattr(annotation, '__parameters__'):
            params = annotation.__parameters__

        if params:
            extra = '\\[{}]'.format(', '.join(format_annotation(param) for param in params))

        if not class_name:
            class_name = annotation_cls.__qualname__.title()

        return '{}`~{}.{}`{}'.format(prefix, module, class_name, extra)
    elif annotation is Ellipsis:
        return '...'
    elif (inspect.isfunction(annotation) and annotation.__module__ == 'typing' and
          hasattr(annotation, '__name__') and hasattr(annotation, '__supertype__')):
        return ':py:func:`~typing.NewType`\\(:py:data:`~{}`, {})'.format(
            annotation.__name__, format_annotation(annotation.__supertype__))
    elif inspect.isclass(annotation) or inspect.isclass(getattr(annotation, '__origin__', None)):
        if not inspect.isclass(annotation):
            annotation_cls = annotation.__origin__

        extra = ''
        try:    # https://github.com/agronholm/sphinx-autodoc-typehints/issues/73
            mro = annotation_cls.mro()
            if Generic in mro or (Protocol and Protocol in mro):
                params = (getattr(annotation, '__parameters__', None) or
                          getattr(annotation, '__args__', None))
                if params:
                    extra = '\\[{}]'.format(', '.join(format_annotation(param) for param in params))
        except TypeError:
            pass
        return ':py:class:`~{}.{}`{}'.format(annotation.__module__, annotation_cls.__qualname__,
                                             extra)

    return str(annotation)


sphinx_autodoc_typehints.format_annotation = format_annotation

def setup(app):
    app.add_config_value('set_type_checking_flag', False, 'html')
    app.connect('builder-inited', sphinx_autodoc_typehints.builder_ready)
    app.connect('autodoc-process-signature', sphinx_autodoc_typehints.process_signature)
    app.connect('autodoc-process-docstring', sphinx_autodoc_typehints.process_docstring)
    return dict(parallel_read_safe=True)
