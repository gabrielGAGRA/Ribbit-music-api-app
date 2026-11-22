/** Represents a domain, validation, or API error in the administrative console. */
export class AdminDomainError extends Error {
  readonly code: 'AUTH' | 'FORBIDDEN' | 'NOT_FOUND' | 'RULE' | 'DUPLICATE' | 'API';

  constructor(
    message: string,
    code: 'AUTH' | 'FORBIDDEN' | 'NOT_FOUND' | 'RULE' | 'DUPLICATE' | 'API' = 'RULE',
  ) {
    super(message);
    this.name = 'AdminDomainError';
    this.code = code;
  }
}
