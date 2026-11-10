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

In-app discovery omits the two configured camera IPs from TCP scan, ARP
revalidation and identity inquiry. Their existing cards remain the place to
inspect/edit/reconnect them. This protects a worker's connection on cameras
that allow only one TCP controller session. It does not prove single-session
ownership against other applications, external CLI probes or simultaneous
configuration changes made elsewhere during a scan.

Opening Settings reads the existing CameraManager connection snapshot instead
of opening extra TCP probe sessions. The displayed online/offline state is
transport state, not proof of VISCA command success or physical camera health.
This avoids blocking the GUI on network connect/join and avoids evicting a
single-session camera's persistent worker merely by opening Settings.
Explicit discovery and post-assignment checks are separate paths; this fix
makes no claim that every external diagnostic has been serialized yet.
