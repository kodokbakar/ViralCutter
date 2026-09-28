import { describe, it, expect } from 'vitest';
import DOMPurify from 'dompurify';

describe('Frontend XSS Security Sanitization', () => {
  const sanitizeSubtitlePreview = (dirtyHtml: string): string => {
    return DOMPurify.sanitize(dirtyHtml, {
      ALLOWED_TAGS: ['div', 'span', 'b', 'i', 'u', 's', 'p'],
      ALLOWED_ATTR: ['style', 'class'],
    });
  };

  it('strips <script> tags completely', () => {
    const malicious = '<div style="color:red"><script>alert("XSS")</script>Hello</div>';
    const clean = sanitizeSubtitlePreview(malicious);
    expect(clean).not.toContain('<script>');
    expect(clean).not.toContain('alert("XSS")');
    expect(clean).toContain('Hello');
  });

  it('strips inline event handlers like onerror and onload', () => {
    const malicious = '<img src="x" onerror="alert(1)" /><span onmouseover="steal()">Text</span>';
    const clean = sanitizeSubtitlePreview(malicious);
    expect(clean).not.toContain('onerror');
    expect(clean).not.toContain('onmouseover');
    expect(clean).not.toContain('alert(1)');
    expect(clean).not.toContain('<img');
    expect(clean).toContain('Text');
  });

  it('strips javascript: pseudoprotocols and unsafe href/src', () => {
    const malicious = '<a href="javascript:alert(1)">Click Me</a><iframe src="javascript:evil()"></iframe>';
    const clean = sanitizeSubtitlePreview(malicious);
    expect(clean).not.toContain('javascript:');
    expect(clean).not.toContain('iframe');
  });

  it('preserves safe styling tags and attributes', () => {
    const safe = '<div style="color: #FFFFFF; font-size: 32px;"><span style="color: #FFD700;">HIGHLIGHT</span> REST OF TEXT</div>';
    const clean = sanitizeSubtitlePreview(safe);
    expect(clean).toContain('style="color: #FFFFFF; font-size: 32px;"');
    expect(clean).toContain('HIGHLIGHT');
    expect(clean).toContain('REST OF TEXT');
  });
});
