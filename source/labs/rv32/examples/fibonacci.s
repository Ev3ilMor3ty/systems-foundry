# The twentieth Fibonacci number. No multiply or runtime library.
    addi a0, zero, 0
    addi a1, zero, 1
    addi t0, zero, 20
loop:
    add t1, a0, a1
    addi a0, a1, 0
    addi a1, t1, 0
    addi t0, t0, -1
    bne t0, zero, loop
    ebreak
