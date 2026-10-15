# Euclid by subtraction: gcd(1071,462) = 21 in a0.
    addi a0, zero, 1071
    addi a1, zero, 462
loop:
    beq a0, a1, done
    bltu a0, a1, smaller
    sub a0, a0, a1
    jal zero, loop
smaller:
    sub a1, a1, a0
    jal zero, loop
done:
    ebreak
