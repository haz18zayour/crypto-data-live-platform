import type { BoardModel } from "./board";
import { CellFace } from "./CellFace";

// A native table, never display: grid on it — that strips the row and column association a
// screen reader depends on. Rows keep registry order and are never sorted by status.
export function BoardMatrix({
  board,
  now = new Date(),
}: {
  board: BoardModel;
  now?: Date;
}) {
  return (
    <table className="board-matrix">
      <caption>Completeness by indicator and asset</caption>
      <thead>
        <tr>
          <th scope="col">Indicator</th>
          {board.assets.map((asset) => (
            <th key={asset} scope="col">
              {asset}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {board.families.map((family) => (
          <tr key={family}>
            <th scope="row">{family.replaceAll("_", " ")}</th>
            {board.cells
              .filter((cell) => cell.family === family)
              .map((cell) => (
                <CellFace key={cell.asset} cell={cell} now={now} />
              ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
