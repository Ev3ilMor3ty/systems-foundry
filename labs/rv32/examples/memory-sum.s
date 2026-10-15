# Write and read 100 little-endian words; a0 = sum(0..99) = 4950.
    lui t0, 1
    addi t1, zero, 100
    addi t2, zero, 0
    addi a0, zero, 0
loop:
    sw t2, 0(t0)
    lw t3, 0(t0)
    add a0, a0, t3
    addi t0, t0, 4
    addi t2, t2, 1
    blt t2, t1, loop
    ebreak
