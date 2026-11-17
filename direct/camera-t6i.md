# Canon Rebel T6i over USB

How stage 1 records on a Canon EOS Rebel T6i (sold as the 750D outside North America), and what
goes wrong. Everything here was observed on one camera with gphoto2 2.5.28 and libgphoto2 2.5.31 on
Linux Mint; `direct/shim.mjs` does all of it for you.

## Setting up the camera

1. Insert an SD card. Without one the camera accepts "record" and records nothing.
2. Push the power switch past ON to the movie position.
3. Connect it to the laptop over USB.
4. Run `direct/launch`. It should list `Canon EOS 750D` and the card's free space.

The camera reports itself as `Canon EOS 750D` (USB id `04a9:32a1`). Its exposure mode reads `P` or
`AV` even in movie mode, so that reading does not tell you where the power switch is.

## The sequence that records

One gphoto2 connection, held open for the whole session:

```
gphoto2 --shell
  set-config capturetarget=1                 # Memory card; the default is Internal RAM
  set-config viewfinder=1                    # live view on; allow about 3 seconds
  set-config movierecordtarget=Card          # recording starts
  get-config movierecordtarget               # "Current: Card" confirms it
  set-config movierecordtarget=None          # recording stops
  wait-event-and-download FILEADDED          # the clip arrives as MVI_nnnn.MP4
```

All three settings matter:

- **One connection.** The camera leaves USB control each time a connection closes, and the recording
  target falls back. Separate `gphoto2` commands, one per step, do not record.
- **Capture target on the card.** With it on Internal RAM the camera reports
  `movierecordtarget` as `Card`, records nothing, and answers the stop with `PTP Device Busy`.
- **Live view on.** Canon bodies only record video with live view running.

`movierecordtarget` reads `SDRAM` after the clip is saved; that is normal.

## What you get

1920x1080, 29.97 fps, H.264 with AAC 48 kHz sound, about 3.7 MB per second. The clip reaches the take
folder about 6 seconds after `cut` for a 9 second take, as `camera.mp4`. gphoto2 removes it from the
card once it is downloaded, so the laptop holds the only copy.

On the first take after `direct/launch` the camera starts up to 9 seconds after the microphone,
because live view is still coming up; wait ten seconds before the first `roll`. On later takes the
two recordings differ by about a quarter of a second. The raw edit aligns them by sound in any case.

## Symptoms

| What you see | Cause | Fix |
| --- | --- | --- |
| `Could not claim the USB device` | The desktop mounted the camera as a storage device (it does this once a card is in) and holds the USB connection | `gio mount -u gphoto2://Canon_Inc._Canon_Digital_Camera/`; the shim does this before it connects |
| Zero storage devices, no folders | No SD card | Insert a card |
| `Current: Card`, but no clip and no change in free space | Capture target is Internal RAM, or live view is off | Set `capturetarget=1` and `viewfinder=1` first |
| `PTP Device Busy` on `movierecordtarget=None` | The camera was not recording | Same as above |
| `PTP Device Busy` on the first command | Sent before the camera settled after connecting | Wait 2 seconds after connecting |
| The camera's screen leaves USB mode | A gphoto2 connection closed | Keep one shell open |
| `roll` answers `CAMERA IS NOT RECORDING` | The camera did not confirm `Card` within 9 seconds | Check the card and the power switch, then `roll` again; the shim reconnects |

## Not covered

- The camera's clock was set to 2015, so clip files carry that date. Set it in the camera's menu.
- Canon stops a movie at 29 minutes 59 seconds or 4 GB; long takes have not been tried.
- Battery life with live view on for a whole session has not been measured.
- Setting `eosmoviemode=1` over USB does not replace the power switch.
