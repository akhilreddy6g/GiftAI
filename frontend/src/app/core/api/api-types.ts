// Names for the API's shapes. Everything here comes from schema.ts, which is generated
// from the backend's OpenAPI schema: if the backend changes a shape, this app stops
// compiling instead of failing at runtime.
import type { components, paths } from './schema';

type Schemas = components['schemas'];

export type ChatRead = Schemas['ChatRead'];
export type ChatCreate = Schemas['ChatCreate'];
export type ChatUpdate = Schemas['ChatUpdate'];
export type ChatTurn = Schemas['ChatTurn'];
export type MessageRead = Schemas['MessageRead'];
export type MessageRole = Schemas['MessageRole'];
export type UserRead = Schemas['UserRead'];
export type Occasion = Schemas['Occasion'];
export type ErrorResponse = Schemas['ErrorResponse'];

export type HttpMethod = 'get' | 'post' | 'patch' | 'delete';

/** The API paths that accept ``Method``. */
export type PathsWith<Method extends HttpMethod> = {
  [Path in keyof paths]: paths[Path][Method] extends { responses: unknown } ? Path : never;
}[keyof paths];

type Operation<Path extends keyof paths, Method extends HttpMethod> = paths[Path][Method];

type JsonContent<Response> = Response extends { content: { 'application/json': infer Body } }
  ? Body
  : null;

/** The body of the operation's success response, or null when it has none (204). */
export type SuccessBody<Path extends keyof paths, Method extends HttpMethod> =
  Operation<Path, Method> extends { responses: infer Responses }
    ? Responses extends { 200: infer Ok }
      ? JsonContent<Ok>
      : Responses extends { 201: infer Created }
        ? JsonContent<Created>
        : null
    : never;

type PathParams<Op> = Op extends { parameters: { path: infer Params } } ? Params : never;
type QueryParams<Op> = Op extends { parameters: { query?: infer Params } } ? Params : never;
type RequestBody<Op> = Op extends { requestBody: { content: { 'application/json': infer Body } } }
  ? Body
  : never;

/** Path parameters, query and body, each required exactly when the operation needs it. */
export type RequestOptions<Path extends keyof paths, Method extends HttpMethod> = ([
  PathParams<Operation<Path, Method>>,
] extends [never]
  ? { path?: never }
  : { path: PathParams<Operation<Path, Method>> }) &
  ([QueryParams<Operation<Path, Method>>] extends [never]
    ? { query?: never }
    : { query?: QueryParams<Operation<Path, Method>> }) &
  ([RequestBody<Operation<Path, Method>>] extends [never]
    ? { body?: never }
    : { body: RequestBody<Operation<Path, Method>> });
