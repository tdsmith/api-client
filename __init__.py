import functools
from typing import Awaitable, Callable, ClassVar, Concatenate, Generator

import attr
import cattrs
import httpx
import trio
import typer
from httpx import Request, Response


@attr.frozen
class Person:
    name: str
    homeworld: str


@attr.define
class SwapiClient:
    sync_client: httpx.Client = httpx.Client()
    async_client: httpx.AsyncClient = httpx.AsyncClient()
    endpoint: ClassVar[str] = "https://swapi.dev/api"

    def _list_people(self) -> Generator[Request, Response, list[Person]]:
        url = self.endpoint + "/people"
        people: list[Person] = []
        while True:
            request = Request("GET", url)
            response = yield request
            response.raise_for_status()
            content = response.json()
            people.extend(cattrs.structure(content["results"], list[Person]))
            if not (url := content["next"]):
                break
        return people

    @staticmethod
    def _sync_wrapper[ClientT: SwapiClient, **P, T](
        f: Callable[Concatenate[ClientT, P], Generator[Request, Response, T]],
    ) -> Callable[Concatenate[ClientT, P], T]:
        @functools.wraps(f)
        def inner(self: ClientT, *args: P.args, **kwargs: P.kwargs) -> T:
            i = f(self, *args, **kwargs)
            request = next(i)
            while True:
                response = self.sync_client.send(request)
                try:
                    request = i.send(response)
                except StopIteration as e:
                    return e.value

        return inner

    @staticmethod
    def _async_wrapper[ClientT: SwapiClient, **P, T](
        f: Callable[Concatenate[ClientT, P], Generator[Request, Response, T]],
    ) -> Callable[Concatenate[ClientT, P], Awaitable[T]]:
        @functools.wraps(f)
        async def inner(self: ClientT, *args: P.args, **kwargs: P.kwargs) -> T:
            i = f(self, *args, **kwargs)
            request = next(i)
            while True:
                response = await self.async_client.send(request)
                try:
                    request = i.send(response)
                except StopIteration as e:
                    return e.value

        return inner

    list_people = _sync_wrapper(_list_people)
    list_people_async = _async_wrapper(_list_people)


def get_people(client: SwapiClient) -> list[Person]:
    people = client.list_people()
    for person in people:
        print(person)
    return people


async def get_people_async(client: SwapiClient) -> list[Person]:
    people = await client.list_people_async()
    for person in people:
        print(person)
    return people


def main(async_: bool):
    client = SwapiClient()
    if async_:
        trio.run(get_people_async, client)
    else:
        get_people(client)


if __name__ == "__main__":
    typer.run(main)
