# Local VISCA regression peer

`runtime.selftest_support.visca_simulator` is a standard-library-only TCP test peer. It binds IPv4 loopback (`127.0.0.1`) on an ephemeral port. It never reads camera configuration or connects to physical cameras. Passing these checks means local regression behavior passed, not that hardware or network installation is validated.

```python
from runtime.selftest_support.visca_simulator import Reply, Step, ScriptedViscaCamera

command = bytes.fromhex('8201043f0201ff')
steps = [Step(command, (
    Reply(bytes.fromhex('9042ff')),
    Reply(bytes.fromhex('a052ff'), delay=1.3),
))]
with ScriptedViscaCamera(steps) as camera:
    # Point only a test worker at camera.host, camera.port.
    # Run the worker/test action here, then stop that worker before context exit.
    pass
```

Each Step consumes one FF-terminated command. `expected=None` accepts any command, but explicit expected bytes give stronger assertions. Reply delays are relative to the previous reply or command. Reply bytes are raw: fragmented frames, concatenated ACKs, Error frames and wrong headers can all be scripted. There is no automatic success reply.

- `Step(command, (Reply(ack),))`: ACK only, socket remains open.
- `Step(command)`: silent peer, TCP remains open.
- `Step(command, close=True)`: orderly remote EOF immediately after receiving the command.
- Multiple steps can span reconnects; remaining steps are consumed by later connections.
- `camera.received`: actual FF-terminated commands, in order.
- `camera.wait_received(count, timeout=2)`: bounded synchronization for UI/worker tests.
- `camera.errors`: peer assertion/processing errors, raised on clean context exit.

The context owns listener and peer thread cleanup. Delays and socket reads check shutdown frequently. Tests should use their own bounded waits and stop workers before leaving the context. Unexpected extra commands are test failures. A late reply to a client that deliberately retired its connection is allowed.

The included real TCP worker regressions cover mixed ACK/Completion headers, delayed Completion, ACK-only, silence, EOF, and the exact two-ACK/different-socket rejection pattern. They preserve Completion as the success condition and never count ACK alone as success.
