i3-msg -t get_tree | jq -r '
  .. | objects
  | select(.window? != null)
  | [.id, (.name // ""), (.window_properties.class // .window_properties.instance // "")]
  | @tsv
'