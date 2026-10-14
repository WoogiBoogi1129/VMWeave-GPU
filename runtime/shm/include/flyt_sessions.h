#ifndef FLYT_SESSIONS_H
#define FLYT_SESSIONS_H
/* v2 application sessions over a single-owner v1 transport. Never reset rings. */
#define FLYT_SESSION_OPEN 4u
#define FLYT_SESSION_CLOSE 5u
#define FLYT_SESSION_CALL 6u
#define FLYT_SESSION_ENVELOPE 24u
#define FLYT_SESSION_MAX_BYTES (16u*1024u*1024u+4096u)
#endif
