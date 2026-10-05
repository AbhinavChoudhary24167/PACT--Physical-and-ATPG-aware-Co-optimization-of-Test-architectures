module compound_scan(CK, test_si, test_se, a, b, c, e, y, test_so);
input CK, test_si, test_se, a, b, c, e;
output y, test_so;
wire d;
AOI211_X1 U_COMPOUND (.A(a), .B(b), .C1(c), .C2(e), .ZN(d));
SDFF_X1 U_FF (.CK(CK), .D(d), .Q(y), .SE(test_se), .SI(test_si));
assign test_so = y;
endmodule
