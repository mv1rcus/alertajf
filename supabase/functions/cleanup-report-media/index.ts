import { createClient } from 'npm:@supabase/supabase-js@2';
import { cleanup } from './cleanup.mjs';

Deno.serve(async (request: Request) => {
  const secret = Deno.env.get('AJF_CLEANUP_SERVICE_ROLE');
  if (!secret || request.headers.get('Authorization') !== `Bearer ${secret}`) {
    return new Response('Unauthorized', {status: 401});
  }
  if (request.method !== 'POST') return new Response('Method not allowed', {status: 405});
  try {
    const client = createClient(Deno.env.get('SUPABASE_URL')!, secret, {
      auth: {persistSession: false, autoRefreshToken: false},
    });
    return Response.json(await cleanup(client));
  } catch {
    return new Response('Cleanup failed; next run will retry', {status: 500});
  }
});
