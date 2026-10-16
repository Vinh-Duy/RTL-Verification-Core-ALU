// Educational SV oracle; portable suite uses a separate integer Python model.
function automatic logic [15:0] alu_expected(input logic [7:0] a, b,
                                             input logic [2:0] opcode);
    longint unsigned aa, bb, value;
    aa = {56'd0, a};
    bb = {56'd0, b};
    case (opcode)
        0: value = aa + bb;
        1: value = (65536 + aa - bb) % 65536;
        2: value = aa * bb;
        3: value = bb == 0 ? 0 : aa / bb;
        4: value = aa & bb;
        5: value = aa | bb;
        6: value = aa ^ bb;
        7: value = aa * (64'd1 << (bb % 8));
        default: value = 0;
    endcase
    return value[15:0];
endfunction
