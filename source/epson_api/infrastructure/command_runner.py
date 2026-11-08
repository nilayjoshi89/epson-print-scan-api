import asyncio
from dataclasses import dataclass

from epson_api.domain.errors import CommandTimeoutError


@dataclass(frozen=True)
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str


class CommandRunner:
    async def run(self, *command: str, timeout: int = 30) -> CommandResult:
        process = await asyncio.create_subprocess_exec(
            *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
        except TimeoutError:
            process.kill()
            await process.wait()
            raise CommandTimeoutError(f"{command[0]} timed out") from None
        return CommandResult(await process.wait(), stdout.decode(errors="replace"), stderr.decode(errors="replace"))
