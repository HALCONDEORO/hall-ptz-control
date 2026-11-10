# Camera command result boundaries

Nonblocking move, zoom, HOME and STOP report queue admission. A successful result
means the worker accepted the frame, not that the camera moved or stopped.
Their message states that execution is not confirmed. A full/rejecting queue or
missing configured endpoint must not return success or create an empty-IP worker.

Confirmed operations still wait for VISCA completion/error/timeout. A queued
command may later fail because the camera or network is unavailable. Do not use
queue admission as evidence of hardware health or successful physical motion.

Workers reject ordinary commands during shutdown. Emergency priority STOPs are
the exception: retained STOPs may be delivered by a successful restart, including
recovery from a stuck old worker. This preserves the existing safety contract;
it is not a guarantee that an offline camera received STOP.

No camera firmware, hardware, live network or deployment was tested in this PR.

The post-assignment camera check sends a bounded, read-only power inquiry via
that endpoint's existing worker queue/session. It does not open a second TCP
connection. Both power ON and STANDBY identify a responding VISCA camera, not
motion readiness. Error, ACK-only, missing/unknown power data and stale results
from a replaced endpoint do not turn the new endpoint's badge green. The check
runs off the GUI thread and results are also endpoint-checked on GUI delivery.
Standalone discovery and external CLI/diagnostic probes remain separate paths.
