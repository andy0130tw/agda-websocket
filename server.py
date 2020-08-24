#!/usr/bin/env python3
import asyncio
import json
import subprocess as _subprocess
import logging
import re
import readline
import shlex
import sys
import traceback

import websockets

from sexpr_parser import parseSexpression


def get_agda_version(agda_path: str='agda'):
    agda_version_str = _subprocess.check_output([agda_path, '--version'], universal_newlines=True)

    matched = re.search(r'version\s+(\d+)\.(\d+)\.(\d+)(-[\w-]+)?', agda_version_str)
    assert matched is not None
    return tuple(map(int, matched.groups()[:3]))

async def agda_interactor(process: asyncio.subprocess.Process):
    assert process.stdin is not None
    assert process.stdout is not None
    data = await process.stdout.readuntil(b'> ')

    matched = re.match(rb'\S*?> ', data)

    if matched is None:
        raise Exception('Cannot extract the prompt string!')

    prompt = matched.group(0)
    assert len(prompt) > 0
    print(f'Prompt detected as "{prompt.decode()}", agda is ready.')

    evt_idle = asyncio.Event()
    evt_idle.set()

    # we shares the agda instance for now, so here is a lock :P
    read_lock = asyncio.Lock()

    async def _write_to_agda(websocket, path):
        try:
            async for recv in websocket:
                inp = recv.lstrip()

                if not inp or inp.startswith('--'):
                    continue

                process.stdin.write(bytes(f'{inp}\n', 'utf-8'))
                # this is only for status checking now
                evt_idle.clear()
                await process.stdin.drain()
        except websockets.exceptions.ConnectionClosed:
            print('Client disconnects abnormally')

    async def _read_from_agda(websocket, path):
        while True:
            # NOTE: the prompt never ends with a newline, which causes
            # newline() to block indefinitely!
            async with read_lock:
                peek = await process.stdout.read(len(prompt))
                if peek == prompt:
                    evt_idle.set()
                    continue

                # the lock ensures atomicity of reading
                data = (peek + await process.stdout.readline()).rstrip()

            try:
                if not data.startswith(b'('):
                    # not an s-expression
                    await websocket.send(json.dumps({'error': data.decode()}))
                    continue

                obj = parseSexpression(data.decode())
                resp = json.dumps(obj)
                await websocket.send(resp)
            except websockets.exceptions.ConnectionClosed:
                # the connection halts before we could send out the response;
                # discard the response
                pass

    async def websocket_handler(websocket, path):
        print('Client connects', path)

        to_task = lambda t: asyncio.create_task(t(websocket, path))
        tasks = list(map(to_task,
            [_read_from_agda, _write_to_agda]))

        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED)

        for t in pending:
            t.cancel()

        print('Client disconnects')

    server = await websockets.serve(websocket_handler, 'localhost', 8765)
    print('WebSocket service launched...')
    await server.wait_closed()


async def create_subprocess_safe(task_generator, *args, **kwargs):
    process = await asyncio.subprocess.create_subprocess_exec(*args, **kwargs)
    try:
        await task_generator(process)
        # await asyncio.wait([task])
    except asyncio.CancelledError:
        print('Bye!')
    except Exception as e:
        print('---------- P A N I C ----------')
        traceback.print_exc()
    finally:
        await process.communicate(b'')
        # process.kill()
        # await process.wait()


async def main():
    logger = logging.getLogger('websockets.server')
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())

    agda_path = 'agda'

    try:
        agda_version = get_agda_version(agda_path)
        print(f'Agda version: {agda_version}')
    except Exception as err:
        print(f'Failed to get Agda version!', file=sys.stderr)
        return

    ret = await create_subprocess_safe(agda_interactor,
        agda_path, '--interaction',
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
