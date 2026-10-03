module input_alias (external_input,
    external_output);
 input external_input;
 output external_output;

 wire internal_input;
 wire internal_output;

 BUF_X1 buffer (.A(internal_input),
    .Z(internal_output));
 assign external_output = internal_output;
endmodule
