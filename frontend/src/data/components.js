import i5 from "../assets/i5.webp";
import ryzen5 from "../assets/ryzen5.webp";
import b760ME from "../assets/b760ME.png";
import b660ME from "../assets/b660ME.png";  
import b550MA from "../assets/b650MA.png";
import coolermaster1 from "../assets/coolermaster(1).webp";
import coolermaster2 from "../assets/coolermaster(2).webp";
import rtx3060 from "../assets/rtx3060.webp";
import rtx4060 from "../assets/rtx4060.webp";
import rtx5080 from "../assets/rtx5080.webp";
import rtx5070ti from "../assets/rtx5070ti.webp";
import adata1 from '../assets/adata710.webp'
import adata2 from "../assets/adata710(2).webp";
import hdd1 from '../assets/wd1tb.webp'
import hdd2 from "../assets/wd1p.webp";
import ram1 from '../assets/d308.webp'
import ram2 from "../assets/d3016.webp";
import psu1 from '../assets/psu650.webp'
import psu2 from "../assets/psu550.webp";
import case1 from  '../assets/cab(1).webp'
import case2 from "../assets/cab(2).webp";
export const componentsData = {
  processor: [
    {
      id: "p1",
      name: "Intel i5 12400",
      price: 10500,
      image: i5,
    },
    {
      id: "p2",
      name: "Intel i5 12400F",
      price: 13500,
      image: i5,
    },
    {
      id: "p3",
      name: "AMD Ryzen 5 5600",
      price: 10200,
      image: ryzen5,
    },
    {
      id: "p4",
      name: "AMD Ryzen 5 5600X",
      price: 11800,
      image: ryzen5,
    },
  ],
  motherboard: [
    {
      id: "m1",
      name: "MSI PRO B760M-E DDR5",
      price: 9125,
      image: b760ME,
    },
    {
      id: "m2",
      name: "MSI PRO B660M-E DDR4",
      price: 8500,
      image: b660ME,
    },
    {
      id: "m3",
      name: "MSI B550M-A Pro Motherboard(DDR4)",
      price: 6000,
      image: b550MA,
    },
    {
      id: "m4",
      name: "B550M PRO-VDH WIFI(DDR4)",
      price: 9500,
      image: b660ME,
    },
  ],
  ram: [
    {
      id: "r1",
      name: "Adata XPG Gammix D30 8GB DDR4 3200MHz (Red)",
      price: 1490,
      image: ram1,
    },
    {
      id: "r2",
      name: "Adata XPG Gammix D30 16GB DDR4 3200MHz (Red)",
      price: 2490,
      image: ram2,
    },
  ],
  gpu: [
    {
      id: "g1",
      name: "Gigabyte RTX 4060 OC 8GB",
      price: 25000,
      image: rtx4060,
    },
    {
      id: "g2",
      name: "Inno3d RTX 3060 12GB",
      price: 24500,
      image: rtx3060,
    },
    {
      id: "g3",
      name: "MSI RTX 5080 OC 16GB GDDR7 White",
      price: 192500,
      image: rtx5080,
    },
    {
      id: "g4",
      name: "GALAX RTX 5070Ti 16gb GDDR7",
      price: 105000,
      image: rtx5070ti,
    },
  ],
  psu: [
    {
      id: "psu1",
      name: "MSI MAG A650BN PSU-650W 80 Plus Bronze",
      price: 4500,
      image: psu1,
    },
    {
      id: "psu2",
      name: "MSI MAG A550BN PSU-550W 80 Plus Bronze",
      price: 3700,
      image: psu2,
    },
  ],
  ps: [
    {
      id: "ps1",
      name: "Adata Legend 710 256GB M.2 NVMe Internal SSD",
      price: 1800,
      image: adata1,
    },
    {
      id: "ps2",
      name: "Adata Legend 710 512GB M.2 NVMe Internal SSD",
      price: 2700,
      image: adata2,
    },
  ],
  ss: [
    { id: "ss1", name: "Western Digital HDD 1TB", price: 3600, image: hdd1 },
    {
      id: "ss2",
      name: "Western Digital HDD 1TB 5400RPM (Purple)",
      price: 4000,
      image: hdd2,
    },
  ],
  cooling: [
    {
      id: "c1",
      name: "Cooler Master Liquid 240L ARGB (White)",
      price: 6500,
      image: coolermaster1,
    },
    {
      id: "c2",
      name: "Cooler Master Liquid 240L ARGB (Black)",
      price: 6100,
      image: coolermaster2,
    },
  ],
  cabinet: [
    {
      id: "cab1",
      name: "Deepcool Macube 110 Cabinet(White)",
      price: 4500,
      image: case1,
    },
    {
      id: "cab2",
      name: "GALAX Revolution-06 Mesh RGB (ATX) Mid-tower",
      price: 4480,
      image: case2,
    },
  ],
};
