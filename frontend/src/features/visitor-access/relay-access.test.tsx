import {screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {beforeEach,describe,expect,it,vi} from "vitest";
import {renderWithProviders} from "@/test/utils";
import {createApiKey} from "@/test/mocks/factories";
import {useAuthStore} from "@/features/auth/hooks/use-auth";
import {AppHeader} from "@/components/layout/app-header";
import {ApiList} from "@/features/apis/components/api-list";
import {CodexConfigButton} from "@/features/codex-config/codex-config-button";
import {AddAccountDialog} from "@/features/accounts/components/add-account-dialog";

describe("native relay role controls",()=>{
  beforeEach(()=>useAuthStore.setState({role:"guest",canWrite:false,authenticated:true}));
  it("hides account/dashboard navigation and admin login for visitors",()=>{
    renderWithProviders(<AppHeader onLogout={vi.fn()} showAdminLogin onAdminLogin={vi.fn()}/>);
    expect(screen.queryByRole("link",{name:/^Accounts/})).not.toBeInTheDocument();
    expect(screen.queryByRole("link",{name:/^Dashboard/})).not.toBeInTheDocument();
    expect(screen.queryByRole("button",{name:/Admin sign/i})).not.toBeInTheDocument();
    expect(screen.getByRole("link",{name:/Reports/i})).toBeInTheDocument();
  });
  it("hides key creation while leaving Codex configuration available",async()=>{
    const keys=[createApiKey()];
    renderWithProviders(<><ApiList apiKeys={keys} selectedKeyId={null} onSelect={vi.fn()} onOpenCreate={vi.fn()}/><CodexConfigButton apiKeys={keys}/></>);
    expect(screen.queryByRole("button",{name:/Create.*key/i})).not.toBeInTheDocument();
    const user=userEvent.setup();
    await user.click(screen.getByRole("button",{name:"Configure Codex"}));
    expect(screen.getByRole("button",{name:"Reset and generate commands"})).toBeDisabled();
    await user.click(screen.getByRole("checkbox"));
    expect(screen.getByRole("button",{name:"Reset and generate commands"})).toBeEnabled();
  });
  it("offers model-source creation inside the add-account dialog",()=>{
    renderWithProviders(<AddAccountDialog open onOpenChange={vi.fn()} onImport={vi.fn()} onAddAccount={vi.fn()} onAddSource={vi.fn()}/>);
    expect(screen.getByRole("button",{name:/Model Source/})).toBeInTheDocument();
  });
});
