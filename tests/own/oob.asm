// SP starts at the top (0x100). [SP,-8] is the last valid 8-byte slot; [SP,-4] runs past the end.
MOV X0, 1
STR X0, [SP, -8]
STR X0, [SP, -4]
RET
