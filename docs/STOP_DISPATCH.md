# STOP dispatch and observers

The event bus has one dedicated, bounded STOP admission handler. Ordinary subscribers remain serial on the normal consumer. They do not execute camera STOP admission and their timing is not a physical-stop guarantee.

Pending STOP events are coalesced by the endpoint key returned by the motion-safety preparation hook. If one STOP is active and two more arrive for the same endpoint before admission catches up, the later pending STOP replaces the earlier pending STOP. The active STOP still completes its admission attempt. For example, admission and ordinary observers see events 1 and 3, not all of 1, 2 and 3.

This is current behavior, not an audit log contract. Do not count ordinary STOP subscriber calls as the number of operator requests. No new counter, telemetry, thread, callback, retry or shutdown behavior is introduced by this documentation and regression test.
