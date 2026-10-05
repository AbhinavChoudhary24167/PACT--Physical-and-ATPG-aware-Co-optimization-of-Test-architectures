module compound_mux(CK, test_si, test_se, a, b, s, y, test_so);
input CK, test_si, test_se, a, b, s;
output y, test_so;
wire d;
MUX2_X1 U_COMPOUND (.A(a), .B(b), .S(s), .Z(d));
SDFF_X1 U_FF (.CK(CK), .D(d), .Q(y), .SE(test_se), .SI(test_si));
assign test_so = y;
endmodule
