/**
 * Typed errors so callers can fail visibly rather than guess (Constitution Art. 7.2).
 */

/** A tool argument was malformed or could not be resolved (names valid options). */
export class InvalidInputError extends Error {
  constructor(message) {
    super(message);
    this.name = "InvalidInputError";
  }
}

/** The data platform returned an error or an unusable response. */
export class UpstreamError extends Error {
  constructor(message) {
    super(message);
    this.name = "UpstreamError";
  }
}
