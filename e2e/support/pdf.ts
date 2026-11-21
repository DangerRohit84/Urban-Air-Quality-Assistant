/**
 * Build a minimal single-page PDF that pypdf can extract text from.
 *
 * The fixture is generated in the test process so the repository never stores
 * a binary fixture and the upload path is exercised with real PDF bytes.
 */

function escapePdfText(text: string): string {
  return text.replace(/\\/g, "\\\\").replace(/\(/g, "\\(").replace(/\)/g, "\\)");
}

function assemble(objects: Buffer[]): Buffer {
  const chunks: Buffer[] = [Buffer.from("%PDF-1.4\n", "latin1")];
  let size = chunks[0].length;
  const offsets: number[] = [];

  objects.forEach((body, index) => {
    offsets.push(size);
    const head = Buffer.from(`${index + 1} 0 obj\n`, "latin1");
    const tail = Buffer.from("\nendobj\n", "latin1");
    chunks.push(head, body, tail);
    size += head.length + body.length + tail.length;
  });

  const xrefStart = size;
  let xref = `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (const offset of offsets) {
    xref += `${String(offset).padStart(10, "0")} 00000 n \n`;
  }
  xref +=
    `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\n` +
    `startxref\n${xrefStart}\n%%EOF\n`;
  chunks.push(Buffer.from(xref, "latin1"));

  return Buffer.concat(chunks);
}

export function textPdf(text: string): Buffer {
  const stream = Buffer.from(
    `BT /F1 12 Tf 72 720 Td (${escapePdfText(text)}) Tj ET`,
    "latin1",
  );
  const objects = [
    Buffer.from("<< /Type /Catalog /Pages 2 0 R >>", "latin1"),
    Buffer.from("<< /Type /Pages /Kids [3 0 R] /Count 1 >>", "latin1"),
    Buffer.from(
      "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] " +
        "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
      "latin1",
    ),
    Buffer.concat([
      Buffer.from(`<< /Length ${stream.length} >>\nstream\n`, "latin1"),
      stream,
      Buffer.from("\nendstream", "latin1"),
    ]),
    Buffer.from(
      "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
      "latin1",
    ),
  ];
  return assemble(objects);
}
