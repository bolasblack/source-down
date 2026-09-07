(* # Reading source

   {% include "examples/reader.mli" lines="9-11" %}
*)

type source = { path : string; contents : string }

let read path =
  try
    let channel = open_in_bin path in
    let contents = Fun.protect
      ~finally:(fun () -> close_in_noerr channel)
      (fun () -> really_input_string channel (in_channel_length channel)) in
    Ok { path; contents }
  with Sys_error message -> Error message
