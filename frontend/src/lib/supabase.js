import { createClient } from "@supabase/supabase-js";

const supabaseUrl =
  import.meta.env.VITE_SUPABASE_URL ||
  "https://ibfvipdqbratgpmieygf.supabase.co";
const supabaseAnonKey =
  import.meta.env.VITE_SUPABASE_ANON_KEY ||
  "sb_publishable_lwN2MR6pFJDDTW9nwi92_w_HxPCyHT3";

export const supabase = createClient(supabaseUrl, supabaseAnonKey);