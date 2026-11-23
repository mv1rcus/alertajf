export const validPath = path => typeof path === 'string' && /^r\/[a-zA-Z0-9][a-zA-Z0-9._-]{0,199}$/.test(path) && !path.includes('..');

// Only server-selected, expired report attachments. Never list/delete a bucket wholesale.
export async function cleanup(client) {
  const {data: paths, error} = await client.rpc('ajf_media_cleanup_candidates');
  if (error) throw new Error('Candidate lookup failed');
  let removed = 0, failed = 0;
  for (const {path} of paths ?? []) {
    if (!validPath(path)) { failed++; continue; }
    const check = await client.rpc('ajf_media_cleanup_eligible', {object_path: path});
    if (check.error || check.data !== true) { failed++; continue; }
    const result = await client.storage.from('relatos-midia').remove([path]);
    if (result.error) { failed++; continue; }
    const ack = await client.rpc('ajf_media_cleanup_ack', {object_path: path});
    if (ack.error) { failed++; continue; }
    removed++;
  }
  return {removed, failed};
}
