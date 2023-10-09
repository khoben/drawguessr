from typing import Protocol, Tuple, Type, Union

Exception_Type = Type[Exception]


class TooManyTriesException(RuntimeError):
    pass


def retry(
    expects: Union[Exception_Type, Tuple[Exception_Type]] = Exception, times: int = 3
):
    """Retry decorator for async functions"""

    def func_wrapper(f):
        from functools import wraps

        @wraps(f)
        async def wrapper(*args, **kwargs):
            exception = None
            for _ in range(times):
                try:
                    return await f(*args, **kwargs)
                except expects as ex:
                    exception = ex
            raise TooManyTriesException(exception) from exception

        return wrapper

    return func_wrapper


class AsyncRetryProtocol(type(Protocol)):
    """Decorate public async class methods with retry decorator"""

    def __new__(cls, name, bases, attrs, **kwargs):
        import asyncio

        exclude = kwargs.get("exclude", [])
        expects = kwargs.get("expects", Exception)
        times = kwargs.get("times", 3)

        for attr_name, attr_value in attrs.items():
            if (
                not attr_name.startswith("_")
                and attr_name not in exclude
                and asyncio.iscoroutinefunction(attr_value)
            ):
                attrs[attr_name] = (
                    retry(expects=expects, times=times))(attr_value)

        return super(AsyncRetryProtocol, cls).__new__(cls, name, bases, attrs)
