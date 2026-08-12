import type { Meta, StoryObj } from "@storybook/react-vite";

import { Dialog } from "../ui/Dialog";
import { Button } from "../ui/Button";
import { useState } from "react";

function DialogDemo({ blockBackdropClose = false }: { blockBackdropClose?: boolean }) {
  const [open, setOpen] = useState(true);
  return (
    <>
      <Button surface="chrome" variant="settings" onClick={() => setOpen(true)}>
        Open dialog
      </Button>
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        className="merge-modal"
        ariaLabelledBy="demo-dialog-title"
        blockBackdropClose={blockBackdropClose}
      >
        <header className="merge-modal-header">
          <h2 id="demo-dialog-title" className="merge-modal-title">
            DEMO DIALOG
          </h2>
          <Button
            surface="close"
            modal="merge"
            ariaLabel="Close"
            disabled={blockBackdropClose}
            onClick={() => setOpen(false)}
          >
            &times;
          </Button>
        </header>
        <div className="merge-modal-body">
          <p className="merge-modal-summary">
            Shared Dialog shell used by merge, note, settings, and QA modals.
          </p>
        </div>
        <footer className="merge-modal-footer">
          <Button
            surface="modal"
            modal="merge"
            variant="ghost"
            onClick={() => setOpen(false)}
          >
            Close
          </Button>
        </footer>
      </Dialog>
    </>
  );
}

const meta = {
  title: "UI/Dialog",
  component: DialogDemo,
  parameters: { layout: "centered" },
} satisfies Meta<typeof DialogDemo>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Open: Story = {};

export const BlockedBackdrop: Story = {
  args: { blockBackdropClose: true },
};
