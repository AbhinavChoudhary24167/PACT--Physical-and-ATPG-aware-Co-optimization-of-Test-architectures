// Self-authored 64-FF debug benchmark. Not research evidence.
module pact_sanity (
    input wire clk,
    input wire rst_n,
    input wire [7:0] data_in,
    output wire [15:0] data_out
);
    reg [15:0] a, b, c, d;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            a <= 16'h0001;
            b <= 16'h00a5;
            c <= 16'h1234;
            d <= 16'h005a;
        end else begin
            a <= {a[14:0], a[15] ^ a[13] ^ data_in[0]};
            b <= b + (a ^ {8'b0, data_in});
            c <= {c[14:0], c[15] ^ c[12] ^ b[4]};
            d <= (d ^ c) + (b & {2{data_in}});
        end
    end
    assign data_out = (a ^ c) + (b & d);
endmodule
