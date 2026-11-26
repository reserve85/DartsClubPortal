/**
 * THE design of the club portal - one place for colours, radius, fonts and
 * component defaults. Change it here and every page follows.
 *
 * Button rule: filled = normal action (brand blue), yellow = edit,
 * red = delete / disable, gray = cancel / back, green = approve / money in.
 * Never a button without background.
 */
import {
  ActionIcon,
  Badge,
  Button,
  Card,
  createTheme,
  InputWrapper,
  type MantineColorsTuple,
  Menu,
  Modal,
  NumberInput,
  Paper,
  Select,
  SegmentedControl,
  Switch,
  TextInput,
  Tooltip,
} from "@mantine/core";
import { DatePickerInput, TimePicker } from "@mantine/dates";

// Club blue (#206bc4) and dart orange (#f76707) as 10-shade palettes.
const brand: MantineColorsTuple = [
  "#e6f1fd", "#cde0f7", "#9cc0ec", "#679ee2", "#3c81d9",
  "#226fd4", "#206bc4", "#0f55a8", "#044b97", "#004086",
];
const dart: MantineColorsTuple = [
  "#fff1e6", "#ffe1cf", "#ffc19e", "#fe9f69", "#fe823c",
  "#fe701f", "#f76707", "#e15a00", "#c94f00", "#af4200",
];
// Dark surfaces (navy instead of Mantine's gray-black).
const dark: MantineColorsTuple = [
  "#d5d8e3", "#b2b7c8", "#8e95ab", "#6b7390", "#4a5170",
  "#343a54", "#272c42", "#1e2233", "#181b28", "#14161f",
];

export const theme = createTheme({
  primaryColor: "brand",
  primaryShade: { light: 6, dark: 5 },
  colors: { brand, dart, dark },
  autoContrast: true,
  defaultRadius: "md",
  cursorType: "pointer",
  fontFamily:
    "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
  headings: { fontWeight: "800" },
  components: {
    Button: Button.extend({ defaultProps: { variant: "filled", radius: "md" } }),
    ActionIcon: ActionIcon.extend({ defaultProps: { variant: "filled", radius: "md" } }),
    Card: Card.extend({ defaultProps: { withBorder: true, radius: "lg", padding: "md" } }),
    Paper: Paper.extend({ defaultProps: { radius: "lg" } }),
    Badge: Badge.extend({ defaultProps: { variant: "light", radius: "sm" } }),
    // Help text below the input everywhere: fields side by side stay aligned.
    InputWrapper: InputWrapper.extend({ defaultProps: { inputWrapperOrder: ["label", "input", "description", "error"] } }),
    TextInput: TextInput.extend({ defaultProps: { size: "md" } }),
    NumberInput: NumberInput.extend({ defaultProps: { size: "md" } }),
    Select: Select.extend({
      defaultProps: { size: "md", allowDeselect: false, comboboxProps: { shadow: "md" } },
    }),
    DatePickerInput: DatePickerInput.extend({ defaultProps: { size: "md", valueFormat: "DD.MM.YYYY" } }),
    TimePicker: TimePicker.extend({ defaultProps: { size: "md", format: "24h" } }),
    SegmentedControl: SegmentedControl.extend({ defaultProps: { radius: "xl" } }),
    Switch: Switch.extend({ defaultProps: { size: "md" } }),
    Menu: Menu.extend({ defaultProps: { shadow: "md", radius: "md", withinPortal: true } }),
    Modal: Modal.extend({ defaultProps: { radius: "lg", centered: true } }),
    Tooltip: Tooltip.extend({ defaultProps: { withArrow: true } }),
  },
});

/** Stable colour per name: a person keeps "their" colour on every page. */
const AVATAR_COLORS = ["brand", "dart", "teal", "grape", "green", "pink", "indigo", "cyan", "violet", "orange"];
export function colorFor(name: string): string {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  return AVATAR_COLORS[h % AVATAR_COLORS.length];
}
